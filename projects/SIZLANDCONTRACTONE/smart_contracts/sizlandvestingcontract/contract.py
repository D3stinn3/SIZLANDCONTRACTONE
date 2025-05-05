from algopy import Account, ARC4Contract, Asset, BoxMap, Global, Txn, arc4, itxn
from algopy.arc4 import Struct


class UserAllocation(Struct):
    total_allocation: arc4.UInt64
    claimed_amount: arc4.UInt64
    start_time: arc4.UInt64
    cliff_time: arc4.UInt64
    vesting_period: arc4.UInt64
    last_claim_time: arc4.UInt64


class SizlandVestingContract(ARC4Contract):
    def __init__(self) -> None:
        self.asa = Asset()
        self.allocations = BoxMap(Account, UserAllocation, key_prefix="")
        self.master_contract = Account()  # Store the master contract address

    @arc4.abimethod
    def initialize(self, master: Account, asset: Asset) -> None:
        # Only creator can initialize
        assert Txn.sender == Global.creator_address, "Only creator can initialize"

        # Set master contract
        self.master_contract = master

        # Opt into asset
        self.opt_into_asset(asset)

    @arc4.abimethod
    def opt_into_asset(self, asset: Asset) -> None:
        # Only allow master contract or app creator to opt the app account into an ASA
        assert (
            Txn.sender == Global.creator_address or Txn.sender == self.master_contract
        ), "Unauthorized"

        # Verify an ASA hasn't already been opted into
        assert self.asa.id == 0, "ASA already opted in"

        # Save ASA ID in global state
        self.asa = asset

        # Submit opt-in transaction: 0 asset transfer to self
        itxn.AssetTransfer(
            asset_receiver=Global.current_application_address,
            xfer_asset=asset,
        ).submit()

    @arc4.abimethod
    def set_allocation(
        self,
        beneficiary: Account,
        total_allocation: arc4.UInt64,
        start_time: arc4.UInt64,
        cliff_time: arc4.UInt64,
        vesting_period: arc4.UInt64,
    ) -> None:
        assert (
            Txn.sender == Global.creator_address
        ), "Only the creator can call this method"
        self.allocations[beneficiary] = UserAllocation(
            total_allocation=total_allocation,
            claimed_amount=arc4.UInt64(0),
            start_time=start_time,
            cliff_time=cliff_time,
            vesting_period=vesting_period,
            last_claim_time=arc4.UInt64(0),
        )

    @arc4.abimethod
    def claim(self) -> None:
        sender = Txn.sender
        current_time = Global.latest_timestamp

        # Check allocation exists
        assert sender in self.allocations, "No allocation found"

        # Copy and access struct fields
        allocation = self.allocations[sender].copy()

        # Native conversions
        last_claim_time = allocation.last_claim_time.native
        cliff_time = allocation.cliff_time.native
        start_time = allocation.start_time.native
        vesting_period = allocation.vesting_period.native
        claimed_amount = allocation.claimed_amount.native
        total_allocation = allocation.total_allocation.native

        # Enforce cliff and cooldown
        assert current_time >= cliff_time, "Cliff not reached"
        assert current_time - last_claim_time >= 10, "Wait before claiming again"

        # Compute vesting
        end_time = start_time + vesting_period
        if current_time >= end_time:
            vested = total_allocation
        else:
            elapsed = current_time - start_time
            vested = (total_allocation * elapsed) // vesting_period

        # Compute claimable amount
        claimable = vested - claimed_amount
        assert claimable > 0, "Nothing to claim"

        # Transfer ASA
        itxn.AssetTransfer(
            asset_receiver=sender, asset_amount=claimable, xfer_asset=self.asa
        ).submit()

        # Update allocation in BoxMap
        self.allocations[sender] = UserAllocation(
            total_allocation=arc4.UInt64(total_allocation),
            claimed_amount=arc4.UInt64(claimed_amount + claimable),
            start_time=arc4.UInt64(start_time),
            cliff_time=arc4.UInt64(cliff_time),
            vesting_period=arc4.UInt64(vesting_period),
            last_claim_time=arc4.UInt64(current_time),
        )
